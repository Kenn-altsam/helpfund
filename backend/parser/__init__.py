# This file makes the 'parser' directory a Python package.
# It also exposes key classes for convenient imports.

from .kgd.kgd_tax_parser import KGDTaxParser
from .kgd.kgd_captcha_solver import create_captcha_solver 