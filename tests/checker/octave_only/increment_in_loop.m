% expect: octave-syntax
count = 0;
for n = 1:10
  if mod(n, 2) == 0
    count++;
  end
end
