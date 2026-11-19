function c = mp_case(name, args, expected, varargin)
% MP_CASE  A test case for a function problem.
%   mp_case(name, args, expected, 'tol', 1e-9, 'alts', {...}, 'hidden', false, 'sigfigs', N, 'size_only', false)
%   args     = cell array of inputs passed to the student's function
%   expected = cell array of expected outputs (one per output checked)
  c = mp_options(varargin, false);
  c.type = 'case';
  c.name = name;
  c.args = args;
  c.expected = expected;
end
