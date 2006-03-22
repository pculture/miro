"""Usefull paths in the democracy source tree."""

import os.path

root_dir = os.path.abspath(os.path.join(__file__, '..', '..', '..', '..'))
portable_dir = os.path.join(root_dir, 'portable')
bittorrent_dir = os.path.join(portable_dir, 'BitTorrent')
dl_daemon_dir = os.path.join(portable_dir, 'dl_daemon')
resource_dir = os.path.join(root_dir, 'resources')
platform_dir = os.path.join(root_dir, 'platform', 'gtk-x11')
frontend_implementation_dir = os.path.join(platform_dir,
        'frontend_implementation')
xine_dir = os.path.join(platform_dir, 'xine')
debian_package_dir = os.path.join(platform_dir, 'debian_package')

__all__ = ['root_dir', 'portable_dir', 'bittorrent_dir', 'dl_daemon_dir',
    'resource_dir', 'platform_dir', 'frontend_implementation_dir', 'xine_dir'
]
