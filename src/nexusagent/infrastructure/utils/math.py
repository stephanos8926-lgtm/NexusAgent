"""Mathematical utility functions for NexusAgent."""

def is_prime(n: int) -> bool:
    """Check if an integer is a prime number.

    An integer is prime if it is greater than 1 and has no positive divisors
    other than 1 and itself.

    Args:
        n: The integer to check.

    Returns:
        True if n is prime, False otherwise.

    Raises:
        TypeError: If n is not an integer.
    """
    if not isinstance(n, int):
        raise TypeError("n must be an integer")

    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6

    return True
