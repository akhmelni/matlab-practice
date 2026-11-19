x = linspace(0, 2*pi, 200);
plot(x, sin(x), x, cos(x));
hold on
xc = [pi/4, 5*pi/4];
plot(xc, sin(xc), 'ko');
xlabel('x');
ylabel('y');
title('sin(x) and cos(x)');
legend('sin(x)', 'cos(x)', 'crossings');
