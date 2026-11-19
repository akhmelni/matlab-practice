% expect: octave-syntax
try
  x = 1;
catch err
  disp(err.message)
end_try_catch
