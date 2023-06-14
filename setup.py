from setuptools import setup, find_packages

setup(
    name='Koloiarov AL AE Thesis',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'torch',
        'torcheval',
        'optuna',
        'torchvision',
        'torchaudio',
        'requests',
        'matplotlib',
        'scikit-learn'
    ]
)