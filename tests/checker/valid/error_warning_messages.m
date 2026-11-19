x = -1;
if x < 0
    warning('neg:val', 'x is negative: %d', x);
end
assert(isnumeric(x), 'x must be numeric');
try
    error('Value %g is not allowed', x);
catch err
    fprintf('Caught: %s\n', err.message);
end
