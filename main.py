
import threading
import time

def task(name, duration):
    print(f"Task {name}: Starting (duration={duration}s)")
    time.sleep(duration)
    print(f"Task {name}: Finished")

if __name__ == "__main__":
    print("Main: Starting concurrent tasks")

    t1 = threading.Thread(target=task, args=("One", 2))
    t2 = threading.Thread(target=task, args=("Two", 3))
    t3 = threading.Thread(target=task, args=("Three", 1))
    t4 = threading.Thread(target=task, args=("Four", 4))

    t1.start()
    t2.start()
    t3.start()
    t4.start()

    t1.join()
    t2.join()
    t3.join()
    t4.join()

    print("Main: All tasks finished")
