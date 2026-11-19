% Fit a line y = a*x + b by least squares
x = [0 1 2 3 4]';
y = [1.1 2.9 5.2 7.1 8.8]';
A = [x, ones(size(x))];
coef = A \ y;
a = coef(1);
b = coef(2);
p = polyfit(x, y, 1);
resid = y - A*coef;
rmsErr = sqrt(mean(resid.^2));
xx = linspace(min(x), max(x), 100);
yy = polyval(p, xx);
N = (A' * A) \ (A' * y);
fprintf('a = %.4f, b = %.4f, rms = %.4f\n', a, b, rmsErr);
