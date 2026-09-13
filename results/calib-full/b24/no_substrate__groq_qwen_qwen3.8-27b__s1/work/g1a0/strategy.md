Strategy:
A 5-round information game over alphabet {A..H,J,K}, 10 symbols.
Round 1: 10 candidates, each = x + one perm of complement:
c1=A B C D E F G H J K
c2=B C D E F G H J K A
c3=C D E F G H J K A B
c4=D E F G H J K A B C
c5=E F G H J K A B C D
c6=F G H J K A B C D E
c7=G H J K A B C D E F
c8=H J K A B C D E F G
c9=J K A B C D E F G H
c10=K A B C D E F G H J

Scoring rules:
- Accept -> done.
- 'r' correct in pos i  =>  pos i is that letter; lock.
- 's' correct => letter correct but all positions in that candidate are locked out (so pos = one of remaining unblocked letters, which has fewer possibilities).

Any valid solution is found in 5 validation calls.