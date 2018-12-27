from __future__ import print_function, division

import pytest

import operator as ops
import numpy as np

from sisl import _array as ar
from sisl.oplist import oplist


pytestmark = [pytest.mark.oplist]


def test_creation():
    l = oplist(range(10))
    assert len(l) == 10
    l = oplist([1, 2])
    assert len(l) == 2
    l = oplist((1, 2))
    assert len(l) == 2
    assert l[0] == 1
    assert l[1] == 2


@pytest.mark.parametrize("op", [ops.add, ops.sub, ops.mul, ops.truediv, ops.pow])
@pytest.mark.parametrize("key1", [1, 2])
@pytest.mark.parametrize("key2", [1, 2])
def test_math(op, key1, key2):
    d = {
        1: oplist([ar.aranged(10), ar.aranged(10)]),
        2: 2,
    }

    l1 = d[key1]
    l2 = d[key2]
    op(l1, l2)


@pytest.mark.parametrize("op", [ops.iadd, ops.isub, ops.imul, ops.itruediv, ops.ipow])
@pytest.mark.parametrize("key", [1, 2])
def test_imath(op, key):
    d = {
        1: oplist([ar.aranged(1, 10), ar.aranged(1, 10)]),
        2: 2,
    }

    l2 = d[key]
    try:
        l1 = oplist([data * 2 for data in l2])
    except:
        l1 = oplist([ar.aranged(1, 10), ar.aranged(2, 3)])
    op(l1, l2)