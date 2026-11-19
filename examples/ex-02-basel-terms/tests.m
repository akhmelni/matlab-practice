function cases = tests()
  cases = {};
  cases{end+1} = mp_value('smallest number of terms', 'n', 1000);
  cases{end+1} = mp_value('the sum at that point', 'total', 1.6439345666815615, 'tol', 1e-9);
end
