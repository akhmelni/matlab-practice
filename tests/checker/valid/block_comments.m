%{
This whole block is a comment.
x += 1; printf("hello") # not code
y = f(x)(2);
%}
x = 1;
  %{
    indented block comment
  %}
%{ this line is just a normal comment, not a block start
y = x + 1;
