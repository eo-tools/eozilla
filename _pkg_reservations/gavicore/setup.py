from setuptools import setup, find_packages

setup(
    name="gavicore",
    version="0.0.1",
    author="Brockmann Consult Development",
    # author_email="info@brockmann-consult.de",
    description="Reserved name for an upcoming EO data processing tool and framework.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
    ],
)
