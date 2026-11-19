t = linspace(0, 2*pi, 200);
figure;
hold on
plot(t, sin(t), 'b-', 'LineWidth', 2);
plot(t, cos(t), 'r--');
xlabel('t (s)');
ylabel('amplitude');
title('Sine and cosine');
legend('sin', 'cos', 'Location', 'best');
grid on
axis tight
hold off
subplot(2, 1, 1);
semilogy(t, exp(t));
subplot(2, 1, 2);
bar([3 5 2]);
