function y = noEnd(x)
% function files may leave out the final end
y = helper(x) + 1;

function h = helper(x)
h = x * 2;
