function [ok, msg] = mp_equal(actual, expected, c)
% MP_EQUAL  Compare a student's value with the expected value.
%   c has fields tol, sigfigs, size_only. Returns ok and a short reason when not equal.
  ok = false;
  msg = '';
  if isnumeric(expected) || islogical(expected)
    if ~(isnumeric(actual) || islogical(actual))
      msg = sprintf('expected a number, got %s', mp_kind(actual));
      return;
    end
    if ~isequal(size(actual), size(expected))
      msg = sprintf('expected size %s, got %s', mp_size(expected), mp_size(actual));
      return;
    end
    if c.size_only
      ok = true;
      return;
    end
    a = double(actual(:));
    e = double(expected(:));
    same = (isnan(a) & isnan(e)) | (a == e);
    if c.sigfigs > 0
      scale = 10 .^ (floor(log10(abs(e))) - c.sigfigs + 1);
      scale(~isfinite(scale) | scale == 0) = 10 ^ (-c.sigfigs);
      close_enough = abs(round(a ./ scale) - round(e ./ scale)) <= 0;
    else
      close_enough = abs(a - e) <= c.tol .* max(1, abs(e));
    end
    good = same | (isfinite(a) & isfinite(e) & close_enough);
    if all(good)
      ok = true;
    else
      bad = find(~good, 1);
      if numel(e) == 1
        msg = 'wrong value';
      else
        msg = sprintf('wrong value at element %d', bad);
      end
    end
  elseif ischar(expected)
    if ~ischar(actual)
      msg = sprintf('expected text, got %s', mp_kind(actual));
    elseif ~strcmp(actual, expected)
      msg = 'wrong text';
    else
      ok = true;
    end
  elseif iscell(expected)
    if ~iscell(actual)
      msg = sprintf('expected a cell array, got %s', mp_kind(actual));
      return;
    end
    if ~isequal(size(actual), size(expected))
      msg = sprintf('expected size %s, got %s', mp_size(expected), mp_size(actual));
      return;
    end
    for k = 1:numel(expected)
      [ok, msg] = mp_equal(actual{k}, expected{k}, c);
      if ~ok
        msg = sprintf('cell %d: %s', k, msg);
        return;
      end
    end
    ok = true;
  elseif isstruct(expected)
    if ~isstruct(actual)
      msg = sprintf('expected a struct, got %s', mp_kind(actual));
      return;
    end
    fe = sort(fieldnames(expected));
    fa = sort(fieldnames(actual));
    if ~isequal(fe, fa)
      msg = 'struct has different fields';
      return;
    end
    for k = 1:numel(fe)
      [ok, msg] = mp_equal(actual.(fe{k}), expected.(fe{k}), c);
      if ~ok
        msg = sprintf('field %s: %s', fe{k}, msg);
        return;
      end
    end
    ok = true;
  else
    ok = isequal(actual, expected);
    if ~ok
      msg = 'wrong value';
    end
  end
end

function s = mp_size(v)
  s = sprintf('%dx', size(v));
  s = s(1:end - 1);
end

function k = mp_kind(v)
  if ischar(v)
    k = 'text';
  elseif iscell(v)
    k = 'a cell array';
  elseif isstruct(v)
    k = 'a struct';
  elseif isa(v, 'function_handle')
    k = 'a function handle';
  else
    k = class(v);
  end
end
