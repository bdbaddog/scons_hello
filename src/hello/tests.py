import subprocess
Import("module")
Import("outputs")


#
# Verify correct output when running 'hello' program.
#
def test_hello_output(silent):
   test_pass = False

   try:
      program = File(outputs["hello"]).abspath

      if module.Options["hello-phrase"] is not None:
         expected = module.Options["hello-phrase"]
      else:
         expected = "Hello World"

      if module.Variables["ADD_EXCLAMATION"]:
         expected += "!"

      expected += "\n"
      output = str(subprocess.check_output([program],
                                           universal_newlines = True))
      if output == expected:
         test_pass = True
   except:
      pass

   return test_pass

outputs["hello"].Test("hello-output", cmd=test_hello_output)
