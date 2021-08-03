# Copyright (C) 2021 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU Affero GPL version 3 or later

from setuptools import find_packages, setup

from binary_gentoo.internal.version import VERSION_STR

if __name__ == '__main__':
    setup(
        name='binary-gentoo',
        version=VERSION_STR,
        license='AGPLv3+',
        description='CLI tools to build Gentoo packages on a non-Gentoo Linux host',
        long_description=open('README.md').read(),
        long_description_content_type='text/markdown',
        author='Sebastian Pipping',
        author_email='sebastian@pipping.org',
        url='https://github.com/hartwork/binary-gentoo',
        python_requires='>=3.8',
        setup_requires=[
            'setuptools>=38.6.0',  # for long_description_content_type
        ],
        install_requires=[
            'PyYAML',
        ],
        tests_require=[
            'freezegun',
            'parameterized',
        ],
        packages=find_packages(),
        entry_points={
            'console_scripts': [
                'gentoo-build = binary_gentoo.internal.cli.build:main',
                'gentoo-clean = binary_gentoo.internal.cli.clean:main',
                'gentoo-local-queue = binary_gentoo.internal.cli.local_queue:main',
                'gentoo-packages = binary_gentoo.internal.cli.packages:main',
                'gentoo-tree-diff = binary_gentoo.internal.cli.tree_diff:main',
                'gentoo-tree-sync = binary_gentoo.internal.cli.tree_sync:main',
            ],
        },
        classifiers=[
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3 :: Only',
        ])
