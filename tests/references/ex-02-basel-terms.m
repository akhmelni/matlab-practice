target = pi^2 / 6;
total = 0;
n = 0;
while abs(target - total) >= 0.001
  n = n + 1;
  total = total + 1 / n^2;
end
fprintf('n = %d, sum = %.6f\n', n, total);
