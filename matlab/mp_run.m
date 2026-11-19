function mp_run(cfg_path)
% MP_RUN  Entry point used by the practice app. Do not call this yourself.
%   Reads a JSON config, runs the student's code (or the tests) and writes:
%     cfg.progress  one JSON line per finished test case (survives a timeout)
%     cfg.out       the final JSON result
  cfg = jsondecode(fileread(cfg_path));
  set(0, 'defaultfigurevisible', 'off');
  result = struct('status', 'ok', 'error', '', 'cases', {{}}, 'nfigures', 0, 'figure_error', '');
  try
    if strcmp(cfg.mode, 'run')
      mp_exec_script(cfg.script);
    else
      result.cases = mp_run_tests(cfg);
    end
  catch err
    result.status = 'error';
    result.error = mp_error_text(err, cfg.workdir);
  end
  [result.nfigures, result.figure_error] = mp_save_figures(cfg.figdir);
  fid = fopen(cfg.out, 'w');
  fprintf(fid, '%s', jsonencode(result));
  fclose(fid);
end

function results = mp_run_tests(cfg)
  results = {};
  cases = tests();
  vars = struct();
  info = struct('vars', struct(), 'nfigures', 0, 'fn', []);
  if strcmp(cfg.kind, 'function')
    info.fn = str2func(cfg.func);
  else
    % Script problems: run the student's script once, then check its variables.
    vars = mp_exec_script(cfg.script);
    info.vars = vars;
  end
  for k = 1:numel(cases)
    c = cases{k};
    r = struct('name', c.name, 'status', 'passed', 'message', '', ...
               'input', '', 'expected', '', 'actual', '', 'hidden', logical(c.hidden));
    if strcmp(c.type, 'case') && ~c.hidden
      r.input = mp_args_text(c.args, cfg.inputs);
    end
    try
      switch c.type
        case 'case'
          r = mp_do_case(c, cfg, r);
        case 'value'
          r = mp_do_value(c, vars, r);
        case 'check'
          info.nfigures = numel(findall(0, 'type', 'figure'));
          [ok, msg] = c.fn(info);
          if ~ok
            r.status = 'failed';
            r.message = msg;
          end
      end
    catch err
      r.status = 'error';
      r.message = mp_error_text(err, cfg.workdir);
    end
    results{end + 1} = r; %#ok<AGROW>
    fid = fopen(cfg.progress, 'a');
    fprintf(fid, '%s\n', jsonencode(r));
    fclose(fid);
  end
end

function r = mp_do_case(c, cfg, r)
  nout = numel(c.expected);
  outs = cell(1, nout);
  fn = str2func(cfg.func);
  if nout == 0
    fn(c.args{:});
    return;
  end
  [outs{:}] = fn(c.args{:});
  [ok, msg, which] = mp_match(outs, c);
  if ~ok
    r.status = 'failed';
    r.message = msg;
    if ~c.hidden
      r.expected = mp_out_text(c.expected, cfg.outputs);
    end
    r.actual = mp_out_text(outs, cfg.outputs);
  end
  if ok && which > 0
    r.message = 'matched an accepted alternative';
  end
end

function r = mp_do_value(c, vars, r)
  if ~isfield(vars, c.varname)
    r.status = 'failed';
    r.message = sprintf('Your script did not set the variable %s.', c.varname);
    return;
  end
  actual = {vars.(c.varname)};
  [ok, msg] = mp_match(actual, c);
  if ~ok
    r.status = 'failed';
    r.message = msg;
    if ~c.hidden
      r.expected = mp_repr(c.expected{1});
      r.actual = mp_repr(actual{1});
    end
  end
end

function [ok, msg, which] = mp_match(outs, c)
% Compare all outputs with the expected cell, then with each alternative.
  options = [{c.expected}, c.alts];
  msg = '';
  which = -1;
  for a = 1:numel(options)
    exp_cell = options{a};
    ok = true;
    for k = 1:numel(exp_cell)
      [ok_k, msg_k] = mp_equal(outs{k}, exp_cell{k}, c);
      if ~ok_k
        ok = false;
        if a == 1
          if numel(exp_cell) > 1
            msg = sprintf('output %d: %s', k, msg_k);
          else
            msg = msg_k;
          end
        end
        break;
      end
    end
    if ok
      which = a - 1;
      return;
    end
  end
end

function s = mp_args_text(args, names)
  parts = cell(1, numel(args));
  for k = 1:numel(args)
    if k <= numel(names)
      parts{k} = sprintf('%s = %s', names{k}, mp_repr(args{k}));
    else
      parts{k} = mp_repr(args{k});
    end
  end
  s = strjoin(parts, ', ');
end

function s = mp_out_text(outs, names)
  if numel(outs) == 1
    s = mp_repr(outs{1});
    return;
  end
  parts = cell(1, numel(outs));
  for k = 1:numel(outs)
    if k <= numel(names)
      parts{k} = sprintf('%s = %s', names{k}, mp_repr(outs{k}));
    else
      parts{k} = mp_repr(outs{k});
    end
  end
  s = strjoin(parts, ', ');
end

function [n, problem] = mp_save_figures(figdir)
  n = 0;
  problem = '';
  figs = findall(0, 'type', 'figure');
  if isempty(figs)
    return;
  end
  nums = zeros(1, numel(figs));
  for k = 1:numel(figs)
    nums(k) = get(figs(k), 'Number');
  end
  [~, order] = sort(nums);
  for k = 1:numel(order)
    try
      print(figs(order(k)), '-dpng', '-r90', fullfile(figdir, sprintf('%d.png', k)));
      n = n + 1;
    catch err
      problem = err.message;
    end
  end
end

function s = mp_error_text(err, workdir)
% Error message plus the line of the student's file where it happened.
  s = err.message;
  where = '';
  for k = 1:numel(err.stack)
    f = strrep(err.stack(k).file, '\', '/');
    if isempty(f)
      continue;
    end
    [folder, base, ext] = fileparts(f);
    in_work = strcmpi(folder, strrep(workdir, '\', '/')) || strcmpi(strrep(folder, '/private/', '/'), strrep(strrep(workdir, '\', '/'), '/private/', '/'));
    if in_work && ~strcmp(base, 'tests') && ~strncmp(base, 'mp_', 3)
      where = sprintf('%s%s line %d', base, ext, err.stack(k).line);
      break;
    end
  end
  s = strrep(s, [strrep(workdir, '\', '/') '/'], '');
  s = strrep(s, [workdir filesep], '');
  if ~isempty(where)
    s = sprintf('Error in %s: %s', where, s);
  end
end
