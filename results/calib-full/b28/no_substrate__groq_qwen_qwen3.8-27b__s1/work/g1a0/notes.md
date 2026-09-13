Setup: alphabet {A..J,K} minus I? Let me re-read: ABCDEFGHJK. Yes 10 chars, no I.

K-count per position (K in exactly 2 positions):
- K K K K: 2
- B K K A: 2  -> I(c2=K)+I(c3=K) + I(c1=B) - I(c4=K?) ... let me just redo.

Uniform scores: A:0, B:1, C:0, D:0, E:0, F:1, G:0, H:0, J:0, K:2.
So only B, F, K are used. Code = some arrangement of 2 Ks, 1 B, 1 F.

Uniform score for char X = (number of K positions if X=K... no) = count of i where c_i = X.
Scores: c is a multiset {K,K,B,F} in some order.

Score for X=K of KKKK: 2 (matches the 2 K positions).
Score for X=B of BBBB: 1.
Score for X=F of FFFF: 1.

Now candidates:
BKKA = [B,K,K,A]: score = I(c1=B)+I(c2=K)+I(c3=K)+I(c4=A) = 2
FKKA = [F,K,K,A]: score = I(c1=F)+I(c2=K)+I(c3=K) = 1
ABKA = [A,B,K,A]: score = I(c2=B)+I(c3=K) = 0
KBKA = [K,B,K,A]: I(c1=K)+I(c2=B)+I(c3=K) = 0
KFBK = [K,F,B,K]: I(c1=K)+I(c2=F)+I(c3=B)+I(c4=K) = 1

From ABKA: c2 != B, c3 != K.
From BKKA: (c1=B)+(c2=K)+(c3=K) = 2. Since c3!=K, c3 must not be K -> so (c2=K)=1 and (c1=B)=1.
Thus c1=B, c2