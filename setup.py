# -*- coding: utf-8 -*-
"""Installer for the imio.zamqp.dms package."""

from setuptools import find_packages
from setuptools import setup


long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CONTRIBUTORS.rst').read(),
    open('CHANGES.rst').read(),
])


setup(
    name='imio.zamqp.dms',
    version='0.17',
    description="zamqp consumer for imio.dms.mail",
    long_description=long_description,
    # Get more from https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: 4.3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
    ],
    keywords='amqp dms document management system',
    author='IMIO',
    author_email='devs@imio.be',
    url='https://github.com/imio/imio.zamqp.dms',
    download_url='https://pypi.org/project/imio.zamqp.dms',
    license='GPL version 2',
    packages=find_packages('src', exclude=['ez_setup']),
    namespace_packages=['imio', 'imio.zamqp'],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'plone.api',
        'Products.GenericSetup>=1.8.2',
        'setuptools',
        'imio.dms.mail',
        'imio.helpers',
        'imio.zamqp.core'
    ],
    extras_require={
        'test': [
            'imio.dms.mail[test]',
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    """,
)
