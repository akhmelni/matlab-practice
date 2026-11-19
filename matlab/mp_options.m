function c = mp_options(opts, hidden_default)
% MP_OPTIONS  Parse name/value options shared by mp_case / mp_value / mp_check.
  c = struct('tol', 1e-9, 'sigfigs', 0, 'alts', {{}}, 'hidden', hidden_default, 'size_only', false);
  if mod(numel(opts), 2) ~= 0
    error('mp:options', 'Options must be name/value pairs.');
  end
  for k = 1:2:numel(opts)
    key = lower(opts{k});
    switch key
      case {'tol', 'sigfigs', 'hidden', 'size_only'}
        c.(key) = opts{k + 1};
      case 'alts'
        c.alts = opts{k + 1};
      otherwise
        error('mp:options', 'Unknown option %s.', key);
    end
  end
end
