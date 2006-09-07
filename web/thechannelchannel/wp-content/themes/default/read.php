<?php get_header(); ?>


<?php get_sidebar(); ?>


<?php include("nav.php") ?>


<div id="inner_content">


<h2>Exclusive Articles</h2>


<?php query_posts('category_name=exclusive-articles&showposts=30');Ê?>

	<?php if (have_posts()) : ?>
		
		<?php while (have_posts()) : the_post(); ?>


<?php if ( in_category('3') ) { ?>

<div class="exclusive_article">

<h2><a href="<?php the_permalink() ?>" rel="bookmark" title="Permanent Link to <?php the_title(); ?>"><?php the_title(); ?></a></h2>

<div class="byline">
<?php the_time('F j') ?> - <?php echo c2c_get_custom('byline'); ?>
</div>

<div class="article_excerpt">
<?php the_excerpt(); ?>
</div>


</div>

<?php } else { ?>
 <?php } ?>
		<?php endwhile; ?>
	<?php else : ?>
	<?php endif; ?>


</div>


<?php get_footer(); ?>
