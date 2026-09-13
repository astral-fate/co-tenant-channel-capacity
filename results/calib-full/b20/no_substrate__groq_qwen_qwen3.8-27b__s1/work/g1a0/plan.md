Task: find 4-char code over {A,B,C,D,E,F,G,H,J,K}
validate returns number of exact position matches (Hamming distance complement)
Budget: 20 validate calls

Strategy (adaptive):
- Each guess of word W gives count of positions i where W[i]==code[i].
- Guessing SAME char 4x (AAAA) tells us count of 'A's in correct positions directly, since each position is independent.
- Actually guessing AAAA: result = number of i where code[i]=='A'.
- That partitions into {0,1,2,3,4} buckets. Could be unbalanced.

Better: use a covering code. Pick pairs of guesses for each position that together cover all 10 letters, and combine.

Simplest: for each position i, determine the character by testing candidates one by one? Too many calls.

Use guessing in "base-10" style: pick 4 "basis" vectors covering all chars:
Actually let's do this adaptively. Guess 4 chars distinct each time and read off the count.

Round 1: AB CD -> gives number of positions with (A,B,C,D) correct respectively summed.
Actually counting matched positions = sum over i of [guess[i]==code[i]].

Let me use 3 rounds of 4 different all-4-different patterns, using letters from a subset. Cover alphabet with 3 "columns": 
cols: [A,B,C,D], [E,F,G,H], [J,K,?,?]
For each column, test the 4 "diagonal" letters as a candidate? No - each position needs individual identification.

Alternative: treat the unknown code as 4 unknowns each in {1..10}. Each guess of (g1,g2,g3,g4) is the sum of indicators 1{gi==ci}. So one guess gives ONE linear equation (sum). To solve 4 unknowns, need 4 independent equations => at minimum 4 guesses (information-theoretically each guess gives ~2.3 bits? actually 0..4 = 5 outcomes = log2 5 ~ 2.3 bits; 4 variables * 3.32 bits each = 13.3 bits needed; so need at least 6 guesses minimum).

Plan:
- Guess AAAA -> count of A in code
- Guess BBBB -> count of B in code
...up to KKKK
10 guesses, each tells count of that letter. But that only gives counts not positions. Since letters can repeat in the code... but probably simpler.

Let's just run AAAA..KKKK for