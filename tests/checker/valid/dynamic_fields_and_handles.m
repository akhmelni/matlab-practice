s = struct('a', 1, 'b', [2 3]);
names = fieldnames(s);
for k = 1:numel(names)
    fld = names{k};
    v = s.(fld)(1);
    fprintf('%s = %g\n', fld, v);
end
f = @(x) x(2);
y = f([4 5 6]);
h = @() disp('called');
h();
