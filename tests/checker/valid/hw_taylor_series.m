% Taylor series for exp(x) and cos(x)
x = 0.5;
N = 10;
approx = 0;
for n = 0:N
    approx = approx + x^n / factorial(n);
end
err = abs(approx - exp(x));
fprintf('exp(%g) ~ %.10f, error %.2e\n', x, approx, err);

c = 0;
term = 1;
n = 0;
while abs(term) > 1e-12
    term = (-1)^n * x^(2*n) / factorial(2*n);
    c = c + term;
    n = n + 1;
end
fprintf('cos(%g) ~ %.12f after %d terms\n', x, c, n);
answer = c;
