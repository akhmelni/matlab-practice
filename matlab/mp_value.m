function c = mp_value(name, varname, expected, varargin)
% MP_VALUE  A check on a variable set by the student's script (value / plot problems).
%   Expected values are hidden from the student unless 'hidden', false is given.
  c = mp_options(varargin, true);
  c.type = 'value';
  c.name = name;
  c.varname = varname;
  c.expected = {expected};
  alts = c.alts;
  for k = 1:numel(alts)
    if ~iscell(alts{k})
      alts{k} = {alts{k}};
    end
  end
  c.alts = alts;
end
