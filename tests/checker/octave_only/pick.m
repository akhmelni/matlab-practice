% expect: octave-function
function y = pick(x)
  if isargout(1)
    y = x;
  end
end
