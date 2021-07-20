import bisect
import math


def possible_orderings(N):
    """
    Given number of order, return total possible order and tried order (heuristic)
    """
    data = [10, 20, 30, 50, 100, 150]
    names = [
        "Total Strands of hair in human's head",
        "Total Stars in the observable universe",
        "Number of Atoms in the human body",
        "Number of atoms in Earth.",
        "All Legal positions in the game of Go",
        "Number of atoms in Milky way galaxy",
    ]
    # binary search on data array with give N
    idx = bisect.bisect_left(data, N)
    idx = idx - 1 if idx == len(data) else idx
    # if N < 9, show total factorial, or else show string
    qty = str(math.factorial(N)) if N < 9 else names[idx]
    return qty, min((idx + 1) * 500, math.factorial(N))


if __name__ == "__main__":
    print(possible_orderings(5))
    print(possible_orderings(25))

