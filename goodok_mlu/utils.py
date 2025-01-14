import os
import sys
import subprocess
import collections
from collections import OrderedDict
import platform
import re
import git
import warnings
import tempfile
import numpy as np


def dict_flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(dict_flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def wide_notebook(percents=70):
    from IPython.display import display, HTML
    if percents < 30:
        percents = 30
    display(HTML("<style>.container { width:" + str(percents) + "% !important; }</style>"))


def watermark(packages=['python', 'virtualenv', 'nvidia', 'cudnn', 'hostname', 'torch'], return_string=True):
    lines = OrderedDict()
    if 'virtualenv' in packages:
        r = None
        if 'PS1' in os.environ:
            r = os.environ['PS1']
        elif 'VIRTUAL_ENV' in os.environ:
            r = os.environ['VIRTUAL_ENV']
        lines['virtualenv'] = r
    if 'python' in packages:
        r = sys.version.splitlines()[0]
        m = re.compile(r'([\d\.]+)').match(r)
        if m:
            r = m.groups()[0]
        lines['python'] = r
    if 'hostname' in packages:
        lines["hostname"] = platform.node()

    def find_in_lines(pip_list, package_name, remove_name=True):
        res = ''
        for line in pip_list:
            if hasattr(line, 'decode'):
                line = line.decode('utf-8')
            if package_name in line and line.startswith(package_name):
                if remove_name:
                    res = package_name.join(line.split(package_name)[1:]).strip()
                else:
                    res = line.strip()
                break
        return res

    if 'nvidia' in packages:
        lines['nvidia driver'] = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]).splitlines()[0]
        try:
            r = subprocess.check_output(["nvcc", "--version"]).splitlines()
            r = find_in_lines(r, 'release', False)
            r = r.split('release')[1].strip()
            lines['nvidia cuda'] = r
        except:
            pass

    if ('cudnn' in packages) and sys.platform.startswith('linux'):
        try:
            with open('/usr/local/cuda/include/cudnn.h', 'r') as f:
                r = f.readlines()
            v1 = find_in_lines(r, '#define CUDNN_MAJOR')
            v2 = find_in_lines(r, '#define CUDNN_MINOR')
            v3 = find_in_lines(r, '#define CUDNN_PATCHLEVEL')
            lines['cudnn'] = "{}.{}.{}".format(v1, v2, v3)
        except:
            pass

    pip_list = subprocess.check_output(["pip", "list"]).splitlines()

    if 'keras' in packages:
        lines['keras'] = find_in_lines(pip_list, 'Keras')

    if 'tensorflow' in packages:
        lines['tensorflow-gpu'] = find_in_lines(pip_list, 'tensorflow-gpu')

    if 'torch' in packages:
        lines['torch'] = find_in_lines(pip_list, 'torch')

    # with git commit hash
    for key in ['sparseconvnet', 'pytorch-lightning']:
        if key in packages:
            line = find_in_lines(pip_list, key)
            try:
                a = re.split(r'\s+', line)
                if len(a) > 1:
                    path = ' '.join(a[1:])
                    repo = git.Repo(path)
                    h = repo.head.object.hexsha
                    line = f"{line} {h}"
            except:
                pass
            lines[key] = line

    parsed = ['python', 'virtualenv', 'nvidia', 'cudnn', 'hostname', 'sparseconvnet', 'pytorch-lightning']
    for key in packages:
        if key not in parsed:
            lines[key] = find_in_lines(pip_list, key)

    res = ["{: <15} {}".format(k + ":", v) for (k, v) in lines.items()]

    s = "\n".join(res)
    print(s)

    if return_string:
        return s


def exec_and_print(command):
    c = command.split(' ')
    MyOut = subprocess.Popen(
        c,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True)
    stdout, stderr = MyOut.communicate()
    print(stdout)
    print(stderr)


def get_gpu_memory_map():
    """Get the current gpu usage.

    Returns
    -------
    usage: dict
        Keys are device ids as integers.
        Values are memory usage as integers in MB.
    """
    result = subprocess.check_output(
        [
            'nvidia-smi', '--query-gpu=memory.used',
            '--format=csv,nounits,noheader'
        ])
    # print(result)
    result = result.decode('utf8')
    # Convert lines into a dictionary
    gpu_memory = [int(x) for x in result.strip().split('\n')]
    gpu_memory_map = dict([("gpu_{}".format(i), v) for i, v in enumerate(gpu_memory)])
    # gpu_memory_map = dict(zip(range(len(gpu_memory)), gpu_memory))
    return gpu_memory_map


def get_gpu_names_map():
    """Get the current gpus name.

    Returns
    -------
    usage: dict
        Keys are device ids as integers.
        Values are memory usage as integers in MB.
    """
    result = subprocess.check_output(
        [
            'nvidia-smi', '--query-gpu=name',
            '--format=csv,nounits,noheader'
        ])
    # print(result)
    result = result.decode('utf8')
    # Convert lines into a dictionary
    gpu_names = [x for x in result.strip().split('\n')]
    gpu_names = dict([("gpu_{}".format(i), v) for i, v in enumerate(gpu_names)])
    # gpu_memory_map = dict(zip(range(len(gpu_memory)), gpu_memory))
    return gpu_names


def gpu_name_by_n(n):
    gpu_names = get_gpu_names_map()
    return gpu_names.get('gpu_{}'.format(n), None)


# TODO: move to trackers
def log_text_as_artifact(tracker, text, destination=None, existed_temp_file=None):
    fd = None
    try:
        fd, path = tempfile.mkstemp()

        with os.fdopen(fd, 'w') as tmp:
            tmp.write(text)

        try:
            tracker.log_artifact(path, destination)
        except Exception as e:
            warnings.warn(f"Can't .log_artifact for tracker {tracker}. {e}", UserWarning)
    except Exception as e:
        warnings.warn(f"Can't .log_text_as_artifact for composer {e}", UserWarning)
    finally:
        if fd is not None:
            os.remove(path)


def is_notebook():
    try:
        # pylint: disable=pointless-statement,undefined-variable
        get_ipython         # noqa: F821
        return True
    except Exception:
        return False


# TODO: move to sparse

def split_coords_features(coords_features):
    coords = coords_features[0]
    features = coords_features[1]

    assert coords.shape[1] == 4
    example_indices = coords[:, 3]
    N = example_indices.max() + 1

    res_coors_features = []

    for i in range(N):
        indices = (example_indices == i)
        coords_i = coords[indices, :3]
        features_i = features[indices]
        res_coors_features.append([coords_i, features_i])
    return res_coors_features


def sparse_to_dense_sgnn(coords, sdf, dims, fillna=np.inf):
    """
    Warning sdf -->  - sdf
    """
    res = np.ones(dims, dtype=np.float32)
    res = res * fillna
    res[coords[:, 0], coords[:, 1], coords[:, 2]] = -sdf
    res = np.expand_dims(res, axis=0)
    return res
