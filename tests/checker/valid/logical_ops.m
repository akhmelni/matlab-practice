a = [1 0 1];
b = [0 0 1];
c = a & b;
d = a | b;
e1 = xor(a, b);
f = ~a;
g = any(a) && ~all(b);
h = isequal(a, b) || isempty(a);
