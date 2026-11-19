function cases = tests()
  cases = {};
  cases{end+1} = mp_check('x has at least 100 points from 0 to 2*pi', @check_x);
  cases{end+1} = mp_check('a figure with at least 2 curves', @check_lines);
end

function [ok, msg] = check_x(info)
  ok = false;
  msg = '';
  if ~isfield(info.vars, 'x')
    msg = 'Your script did not set the variable x.';
    return;
  end
  x = info.vars.x;
  if numel(x) < 100
    msg = sprintf('x has only %d points.', numel(x));
  elseif abs(min(x)) > 1e-9 || abs(max(x) - 2 * pi) > 1e-9
    msg = 'x should go from 0 to 2*pi.';
  else
    ok = true;
  end
end

function [ok, msg] = check_lines(info)
  ok = info.nfigures >= 1 && numel(findall(0, 'type', 'line')) >= 2;
  msg = '';
  if ~ok
    msg = 'Expected a figure with at least two plotted curves.';
  end
end
