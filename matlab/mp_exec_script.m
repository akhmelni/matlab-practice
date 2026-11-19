function mp__vars = mp_exec_script(mp__name)
% MP_EXEC_SCRIPT  Run a student script in its own workspace and return its variables.
  eval(mp__name);
  mp__vars = struct();
  mp__names = who;
  for mp__k = 1:numel(mp__names)
    mp__n = mp__names{mp__k};
    if strncmp(mp__n, 'mp__', 4)
      continue;
    end
    mp__vars.(mp__n) = eval(mp__n);
  end
end
