import os
import re

img_paths = None

MD_LINK_PATTERN = re.compile(r'\[(.*?)\]\((.*?)\)')


def _load_img_ext_config():
    global img_paths
    if img_paths is None:
        str_img_ext_count = os.environ.get('IMG_PATHS_COUNT')
        if not str_img_ext_count or not str_img_ext_count.isdigit():
            img_paths = []
        else:
            img_paths = []
            for i in range(int(str_img_ext_count)):
                img_paths.append((os.environ.get('IMG_PATHS_' + str(i+1) + '_DIR'),
                                  os.environ.get('IMG_PATHS_' + str(i+1) + '_REF')))
        img_paths = img_paths[::-1]
    return img_paths


def resolve_img_path_dir(img_file_name):
    """
    Search img_file_name in all configured image paths
    """
    img_paths = _load_img_ext_config()
    for dirdef in img_paths:
        path = 'app' + os.path.join(dirdef[0], img_file_name)
        if os.path.exists(path):
            return dirdef
    return '', ''


def parse_inline_link(link_text):
    m = re.search(MD_LINK_PATTERN, link_text)
    return (link_text[:m.start()] + '<a href="' + m.group(2) +'">' + m.group(1) + '</a>' + link_text[m.end():]) if m else link_text
