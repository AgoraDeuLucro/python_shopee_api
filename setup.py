from setuptools import setup, find_packages

with open("README.md", "r") as arq:
    readme = arq.read()

setup(
    name='py_shopee_sp',
    version='0.0.1',
    license='MIT License',
    author='Yuri Gomes',
    author_email='yurialdegomes@gmail.com',
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords='shopee vendedor',
    description='Wrapper não oficial da Shopee API para vendedores',
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=['requests'],
    python_requires='>=3.10',
)
