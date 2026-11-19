x = linspace(0, 1, 5);
y = square(x);
disp(y)
z = cube(2);

function out = square(in)
    out = in.^2;
end

function out = cube(in)
    out = in.^3;
end
