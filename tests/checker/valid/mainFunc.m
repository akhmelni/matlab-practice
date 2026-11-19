function y = mainFunc(x)
%MAINFUNC Calls a helper.
    y = helper(x) + other(x);
end

function h = helper(x)
    h = 2 * x;
end

function o = other(x)
    o = x - 1;
end
