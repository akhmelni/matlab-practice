% expect: octave-syntax
function n = tick()
  persistent count = 0;
  count = count + 1;
  n = count;
end
