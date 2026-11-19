x = 1:5;
plot(x, x.^2, 'Color', [0 0 1], 'LineWidth', 1.5);
opts = optimset('TolX', 1e-8);
xm = fminsearch(@(t) (t - 2).^2, 0, opts);
