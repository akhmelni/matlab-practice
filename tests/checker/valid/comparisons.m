x = 3;
y = 4;
if x ~= y && x <= y && y >= x || x == y
    disp('compare')
end
m = ~(x > y);
n = ~isempty(x);
