<?php
function TackOn ($tackon) {
  $magicNumber = 560097380;

  function packint32($int) {
    return pack("V",$int);
  }

  $len = strlen($tackon);
  $crc = crc32($tackon);
  return $tackon.packint32($crc).packint32($len).packint32($magicNumber);
}
?>
