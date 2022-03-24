import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="expsuite",  # This is the name of the package
    version="0.1.0",  # The initial release version
    author="Thomas Rueckstiess",  # Full name of the author
    description="PyExperimentSuite is an open source software tool written in Python, that supports scientists, engineers and others to conduct automated software experiments on a larger scale with numerous different parameters",
    long_description=long_description,  # Long description read from the the readme file
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),  # List of all python modules to be installed
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],  # Information to filter the project on PyPi website
    python_requires=">=3.6",  # Minimum version requirement of the package
    py_modules=["expsuite"],  # Name of the python package
    package_dir={"": "expsuite/src"},  # Directory of the source code of the package
    install_requires=["numpy"],  # Install other dependencies if any
)
