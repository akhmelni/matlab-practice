x = 1:5;
plot(x, x.^2, LineWidth=2, Color='r');
s = 'Hello';
if contains(s, 'hello', IgnoreCase=true)
    disp('found')
end
