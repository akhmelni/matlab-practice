rng(1);
tic;
a = rand(3);
b = randn(1, 5);
c = randi(10, 2, 2);
elapsed = toc;
s = num2str(elapsed);
msg = sprintf('took %s s', s);
disp(msg)
warning('off', 'all');
