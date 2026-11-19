% expect: script-local-functions
x = 2;
function y = sq(x)
  y = x^2;
end
disp(sq(x))
