function s = mp_repr(v)
% MP_REPR  Short, readable text for a value (shown to the student).
  maxlen = 300;
  if ischar(v)
    s = ['''' v ''''];
  elseif isnumeric(v) || islogical(v)
    if isempty(v)
      s = sprintf('[] (%s)', mp_sz(v));
    elseif ndims(v) > 2 || numel(v) > 60
      s = sprintf('%s %s array', mp_sz(v), class(v));
    else
      s = mat2str(v, 8);
    end
  elseif iscell(v)
    if numel(v) <= 6
      parts = cell(1, numel(v));
      for k = 1:numel(v)
        parts{k} = mp_repr(v{k});
      end
      s = ['{' strjoin(parts, ', ') '}'];
    else
      s = sprintf('%s cell array', mp_sz(v));
    end
  elseif isstruct(v)
    s = ['struct with fields: ' strjoin(fieldnames(v)', ', ')];
  elseif isa(v, 'function_handle')
    s = func2str(v);
  else
    s = sprintf('%s %s', mp_sz(v), class(v));
  end
  if numel(s) > maxlen
    s = [s(1:maxlen) '...'];
  end
end

function s = mp_sz(v)
  s = sprintf('%dx', size(v));
  s = s(1:end - 1);
end
