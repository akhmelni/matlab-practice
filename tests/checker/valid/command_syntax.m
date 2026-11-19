clear all
close all
clc
format long
x = linspace(0, 1, 11);
figure
hold on
grid on
plot(x, x.^2)
axis equal
axis([0 1 0 1])
hold off
format short g
warning off
