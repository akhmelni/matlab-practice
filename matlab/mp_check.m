function c = mp_check(name, fn, varargin)
% MP_CHECK  A custom check. fn receives a struct with fields
%   .fn (handle to the student's function, function problems), .vars (script variables),
%   .nfigures (number of figures drawn) and returns [ok, message].
  c = mp_options(varargin, true);
  c.type = 'check';
  c.name = name;
  c.fn = fn;
end
