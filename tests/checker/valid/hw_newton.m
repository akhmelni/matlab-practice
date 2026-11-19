f = @(x) x.^3 - 2*x - 5;
df = @(x) 3*x.^2 - 2;
x = 2;
for it = 1:50
    dx = f(x) / df(x);
    x = x - dx;
    if abs(dx) < 1e-12
        break;
    end
end
root = x;
fprintf('root = %.12f after %d iterations\n', root, it);
