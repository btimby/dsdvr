import os
import shutil
import glob
import tempfile

from os.path import dirname, splitext, basename
from os.path import join as pathjoin


def get_recordings(path):
    '''
    Gets a sorted list of files matching "recording*.mpeg" from the given
    directory or the directory containing the given file. This function is able
    to skip gaps in the numbering of files.
    '''
    # Special filename invokes special handling...
    if basename(path) != 'recording0.mpeg':
        return [path]

    path = dirname(path)
    file_names = glob.glob(pathjoin(path, 'recording*.mpeg'))
    numbers, nummap = [], {}

    for fn in file_names:
        name = splitext(basename(fn))[0]
        number = int(name[9:])
        numbers.append(number)
        nummap[number] = fn

    numbers.sort()

    # Return sorted paths.
    return [pathjoin(path, nummap[i]) for i in numbers]


def combine_recordings(path, delete=True):
    '''
    Concatenate src_paths to dst_path. Optionally delete src_paths.
    '''
    file_names = get_recordings(path)

    if not file_names or len(file_names) == 1:
        return

    dst_path, src_paths = file_names[0], file_names[1:]
    if src_paths:
        with tempfile.NamedTemporaryFile(
                dir=dirname(dst_path), delete=False) as t:
            for src_path in src_paths:
                with open(src_path, 'rb') as src:
                    shutil.copyfileobj(src, t)

        os.remove(dst_path)
        os.rename(t.name, dst_path)

    if delete:
        for src_path in src_paths:
            os.remove(src_path)


def get_next_recording(path):
    '''
    Get the name for the next recording file in the sequence. Path can be a
    file or directory. Assumes files named "recording*.mpeg".
    '''
    file_names = get_recordings(path)
    path = dirname(path)

    if file_names:
        # Increment the number from the last file.
        next_number = int(basename(file_names[-1])[9:-5]) + 1

    else:
        # Empty directory, start with 0
        next_number = 0

    return pathjoin(path, 'recording%i.mpeg' % next_number)


def last_3_lines(data):
    if callable(getattr(data, 'readlines', None)):
        return data.readlines()[-3:]

    if callable(getattr(data, 'read', None)):
        data = data.read()

    return os.newline.join(data.splitlines()[-3:])


def get_program_filename(program):
    '''
    Build a filesystem path for the given media item.
    '''
    title = program.title.replace(' ', '.')
    airtime = program.start.strftime('%m-%d-%Y-%H:%M')
    # unique = ''.join(
    #     random.choices(string.ascii_letters + string.digits, k=6))
    return pathjoin(title, airtime, 'recording0.mpeg')


def parse_program_filename(path):
    '''
    The reverse of get_media_filename().
    '''
    title, airtime, _ = path.split('/')
    title = title.replace('.', ' ')
    return title, airtime
