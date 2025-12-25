import Algorithme_Interpreter as AI


class Testing():

    Interpret = AI.AlgorithmeInterpreter()

    def test(self):
        print("Starting testing add function\n")
        plateau_init = [0, 0, 1, 1]
        code_ids = [15,9,1,3,16,6,16,17]
        plateau, lignes_executees = self.Interpret.executer(code_ids, plateau_init)

        print("Algoritme crée:")
        self.Interpret.print_algo(code_ids)

        print(f"\nEtat initial du plateau : {plateau_init}\n Etat aprés execution : {plateau}\n")
        print("Ending  testing add function\n")


if __name__ == '__main__':
    test = Testing()
    test.test()