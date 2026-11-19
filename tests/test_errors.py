import pytest

from matlab_practice.errors import matlab_message

CASES = [
    ("x(5): out of bound 3 (dimensions are 1x3)",
     "Index exceeds the number of array elements. Index must not exceed 3."),
    ("A(3,_): out of bound 2 (dimensions are 2x2)",
     "Index in position 1 exceeds array bounds. Index must not exceed 2."),
    ("x(_,5): out of bound 3 (dimensions are 1x3)",
     "Index in position 2 exceeds array bounds. Index must not exceed 3."),
    ("index (3,_): out of bound 2 (dimensions are 2x2)",
     "Index in position 1 exceeds array bounds. Index must not exceed 2."),
    ("x(0): subscripts must be either integers 1 to (2^63)-1 or logicals",
     "Array indices must be positive integers or logical values."),
    ("'foo' undefined near line 1, column 1", "Unrecognized function or variable 'foo'."),
    ("operator +: nonconformant arguments (op1 is 1x2, op2 is 1x3)",
     "Arrays have incompatible sizes for this operation."),
    ("vertical dimensions mismatch (1x2 vs 1x3)", "Dimensions of arrays being concatenated are not consistent."),
    ("structure has no member 'b'", 'Unrecognized field name "b".'),
    ("@<anonymous>: function called with too many inputs", "Too many input arguments."),
    ("my own error message", "my own error message"),
]


@pytest.mark.parametrize("octave, matlab", CASES)
def test_translation(octave, matlab):
    assert matlab_message(octave) == matlab


def test_prefix_kept():
    msg = "Error in myLinInterp.m line 5: y(5): out of bound 4 (dimensions are 4x1)"
    assert matlab_message(msg) == ("Error in myLinInterp.m line 5: Index exceeds the number of array elements. "
                                   "Index must not exceed 4.")


def test_matrix_multiply():
    assert matlab_message("operator *: nonconformant arguments (op1 is 1x2, op2 is 1x2)").startswith(
        "Incorrect dimensions for matrix multiplication")


def test_syntax_error():
    out = matlab_message("syntax error near line 3, column 0 in file /tmp/x/myLinInterp.m")
    assert out.startswith("Invalid syntax in myLinInterp.m near line 3")
