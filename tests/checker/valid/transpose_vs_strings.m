% transpose after names, numbers, brackets, end, and other transposes
A = magic(3);
B = A';
C = A'';
v = [1 2 3]';
w = v.';
x = 2';
y = A(end, :)';
z = {'one', 'two'};
s = [z{1} ' and ' z{2}];
t = ['abc' 'def'];
u = [v' v'];
q = (A + B)';
r = A(:, 1)' * A(:, 2);
c = {A', 'text'};
