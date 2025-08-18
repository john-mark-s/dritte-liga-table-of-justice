"""
Setup script for 3. Liga Table of Justice
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

setup(
    name="3liga-table-of-justice",
    version="1.0.0",
    description="Expected Goals (xG) and Expected Points (xP) analytics for German 3. Liga",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/3liga-table-of-justice",
    
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    install_requires=[
        "pandas>=2.1.0,<3.0.0",
        "numpy>=1.24.0,<2.0.0", 
        "scipy>=1.11.0,<2.0.0",
        "requests>=2.31.0,<3.0.0",
        "beautifulsoup4>=4.12.0,<5.0.0",
        "selenium>=4.15.0,<5.0.0",
        "chromedriver-autoinstaller>=0.6.0,<1.0.0",
        "plotly>=5.17.0,<6.0.0",
        "dash>=2.14.0,<3.0.0",
        "dash-bootstrap-components>=1.5.0,<2.0.0",
        "python-dotenv>=1.0.0,<2.0.0",
        "pyyaml>=6.0.1,<7.0.0",
    ],
    
    extras_require={
        "dev": [
            "pytest>=7.4.0,<8.0.0",
            "black>=23.9.0,<24.0.0",
            "flake8>=6.1.0,<7.0.0",
        ]
    },
    
    entry_points={
        "console_scripts": [
            "3liga-toj=main:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Sports/Analytics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    
    python_requires=">=3.8",
    
    keywords="football soccer bundesliga xg expected-goals analytics dashboard",
    
    project_urls={
        "Bug Reports": "https://github.com/yourusername/3liga-table-of-justice/issues",
        "Source": "https://github.com/yourusername/3liga-table-of-justice",
        "Documentation": "https://github.com/yourusername/3liga-table-of-justice#readme",
    },
)