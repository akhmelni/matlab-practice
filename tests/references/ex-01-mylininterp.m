function [Y] = myLinInterp(x,y,X)
Y = zeros(size(X));
for k = 1:numel(X)
  i = find(x <= X(k), 1, 'last');
  if i == numel(x)
    Y(k) = y(end);
  else
    Y(k) = y(i) + (y(i+1) - y(i)) * (X(k) - x(i)) / (x(i+1) - x(i));
  end
end
end
